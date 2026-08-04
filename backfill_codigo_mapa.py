#!/usr/bin/env python3
"""
backfill_codigo_mapa.py — preenche mapa_produtos.codigo casando por nome.

Script AVULSO: não é importado pelo app e não deve ser. Roda em dry-run por
padrão; só escreve com --apply.

FONTE DOS CÓDIGOS
-----------------
O padrão é `estoque_mestre`, que é onde os códigos da CAMDA (ex.: US254185)
de fato vivem — `estoque_mestre.codigo` é TEXT PRIMARY KEY. A planilha
`produtos_CAMDA.xlsx` do repositório NÃO serve como fonte: suas colunas são
Produto / Princípio Ativo / Grupo Químico / Mecanismo de Ação / Grupo HRAC,
sem nenhuma coluna de código. O modo `--source xlsx` existe para uma planilha
que traga coluna de código, e falha com mensagem clara quando não houver.

CASAMENTO POR NOME
------------------
Os nomes do mapa são cadastrados encurtados, sem o prefixo de categoria
('BORAL 500 SC 20L' no mapa contra 'HERBICIDA BORAL 500 SC 20L' no estoque).
Por isso o match vai em camadas, da mais forte para a mais fraca:

  1. igualdade exata normalizada
  2. o nome do estoque TERMINA com o nome do mapa (o caso do prefixo)
  3. o nome do estoque CONTÉM o nome do mapa

Vale a primeira camada que produzir candidatos. Um único candidato → casado;
mais de um → ambíguo (nunca escreve, é reportado para decisão humana);
nenhum em camada alguma → não encontrado.

USO
---
    python backfill_codigo_mapa.py                  # dry-run, fonte estoque_mestre
    python backfill_codigo_mapa.py --apply          # grava
    python backfill_codigo_mapa.py --apply --force  # grava sobrescrevendo códigos
    python backfill_codigo_mapa.py --orfaos         # só o diagnóstico de órfãos
    python backfill_codigo_mapa.py --source xlsx --xlsx planilha_com_codigo.xlsx

Credenciais vêm de .streamlit/secrets.toml, do .env ou do ambiente
(TURSO_DATABASE_URL / TURSO_AUTH_TOKEN). Sem elas, cai no camda_local.db.
"""

import argparse
import os
import re
import sys
import unicodedata
from collections import defaultdict

_AQUI = os.path.dirname(os.path.abspath(__file__))
LOCAL_DB_PATH = os.path.join(_AQUI, "camda_local.db")


# ── Conexão ───────────────────────────────────────────────────────────────────

def _get_secret(key: str) -> str:
    """Lê de .streamlit/secrets.toml, do .env ou do ambiente — nessa ordem."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    caminho = os.path.join(_AQUI, ".streamlit", "secrets.toml")
    if os.path.exists(caminho):
        try:
            try:
                import tomllib
            except ModuleNotFoundError:
                import tomli as tomllib
            with open(caminho, "rb") as fh:
                valor = tomllib.load(fh).get(key)
            if valor:
                return str(valor)
        except Exception:
            pass
    return os.environ.get(key, "")


def conectar():
    """Abre a mesma conexão que o app usa (réplica embarcada + sync)."""
    try:
        import libsql
    except ModuleNotFoundError:
        raise SystemExit(
            "ERRO: módulo 'libsql' não instalado.\n"
            "  pip install -r requirements.txt"
        )

    url = _get_secret("TURSO_DATABASE_URL")
    token = _get_secret("TURSO_AUTH_TOKEN")

    ja_existia = os.path.exists(LOCAL_DB_PATH)
    if url and token:
        conn = libsql.connect(LOCAL_DB_PATH, sync_url=url, auth_token=token)
        conn.sync()
        print(f"→ conectado ao Turso ({url.split('//')[-1][:40]}…)")
    else:
        conn = libsql.connect(LOCAL_DB_PATH)
        print(f"→ MODO LOCAL: {LOCAL_DB_PATH} "
              "(sem TURSO_DATABASE_URL/TURSO_AUTH_TOKEN)")
        if not ja_existia:
            # Conectar já cria o arquivo vazio. Deixá-lo para trás faz a
            # próxima execução COM credenciais falhar com "invalid local
            # state: db file exists but metadata file does not".
            print(f"  ATENÇÃO: {os.path.basename(LOCAL_DB_PATH)} não existia e "
                  "foi criado vazio por esta conexão.\n"
                  "  Configure TURSO_DATABASE_URL/TURSO_AUTH_TOKEN e apague "
                  "esse arquivo antes de rodar de novo.")
    return conn


_TABELAS_NECESSARIAS = ("mapa_produtos", "estoque_mestre")


def checar_tabelas(conn, tabelas=_TABELAS_NECESSARIAS):
    """Falha cedo e com mensagem clara se o banco não tiver as tabelas."""
    existentes = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    faltando = [t for t in tabelas if t not in existentes]
    if faltando:
        raise SystemExit(
            f"ERRO: banco sem a(s) tabela(s): {', '.join(faltando)}.\n"
            f"  Tabelas encontradas: {', '.join(sorted(existentes)) or '(nenhuma)'}\n"
            "  Provável causa: rodou sem credenciais e caiu num camda_local.db "
            "vazio.\n"
            "  Configure TURSO_DATABASE_URL e TURSO_AUTH_TOKEN "
            "(.streamlit/secrets.toml, .env ou ambiente) e tente de novo."
        )


# ── Normalização ──────────────────────────────────────────────────────────────

def norm_codigo(codigo):
    """Forma canônica de gravação: UPPER(TRIM()). Vazio vira None."""
    if codigo is None:
        return None
    texto = str(codigo).strip().upper()
    return texto or None


def norm_nome(nome) -> str:
    """Normaliza nome para comparação: sem acento, maiúsculo, espaço colapsado."""
    if nome is None:
        return ""
    texto = unicodedata.normalize("NFKD", str(nome))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.upper().strip()
    return re.sub(r"\s+", " ", texto)


# ── Fontes de código ──────────────────────────────────────────────────────────

def carregar_do_estoque(conn) -> list:
    """Retorna [(codigo, produto)] de estoque_mestre, ignorando artefatos AUTO_."""
    rows = conn.execute(
        "SELECT codigo, produto FROM estoque_mestre "
        "WHERE codigo IS NOT NULL AND produto IS NOT NULL"
    ).fetchall()
    fonte = []
    for cod, prod in rows:
        cod_n = norm_codigo(cod)
        # AUTO_* são registros de import mal-parseado; o dashboard já os
        # exclui da busca e não devem virar código de produto no mapa.
        if not cod_n or cod_n.startswith("AUTO_") or not str(prod).strip():
            continue
        fonte.append((cod_n, str(prod)))
    return fonte


_COLS_CODIGO = ("codigo", "código", "cod", "cód", "sku", "item", "produto_id",
                "codigo_produto", "código do produto", "codigo do produto")
_COLS_NOME = ("produto", "descricao", "descrição", "nome", "produto_nome")


def carregar_do_xlsx(caminho: str) -> list:
    """Retorna [(codigo, produto)] de uma planilha que tenha coluna de código."""
    import pandas as pd

    if not os.path.exists(caminho):
        raise SystemExit(f"ERRO: planilha não encontrada: {caminho}")

    fonte, abas_vistas = [], []
    for aba, df in pd.read_excel(caminho, sheet_name=None).items():
        cols = {norm_nome(c).lower(): c for c in df.columns}
        abas_vistas.append(f"{aba} {list(df.columns)}")
        col_cod = next((cols[k] for k in _COLS_CODIGO if k in cols), None)
        col_nom = next((cols[k] for k in _COLS_NOME if k in cols), None)
        if not col_cod or not col_nom:
            continue
        for _, linha in df.iterrows():
            cod = norm_codigo(linha[col_cod])
            nome = str(linha[col_nom] or "").strip()
            if cod and nome:
                fonte.append((cod, nome))

    if not fonte:
        raise SystemExit(
            f"ERRO: nenhuma aba de '{caminho}' tem coluna de código + coluna de "
            f"nome.\nAbas encontradas:\n  " + "\n  ".join(abas_vistas) +
            "\n\nA planilha produtos_CAMDA.xlsx do repositório é a tabela de "
            "princípios ativos e não contém código de produto — use "
            "--source estoque (padrão), que lê estoque_mestre.codigo."
        )
    return fonte


# ── Casamento ─────────────────────────────────────────────────────────────────

def casar(nome_mapa: str, indice_exato: dict, fonte_norm: list):
    """
    Casa um nome do mapa contra a fonte, em camadas.

    Retorna (lista_de_codigos_candidatos, camada). A lista vem sem repetição
    e ordenada; camada é 'exato', 'sufixo', 'contem' ou None.
    """
    alvo = norm_nome(nome_mapa)
    if not alvo:
        return [], None

    exatos = indice_exato.get(alvo)
    if exatos:
        return sorted(set(exatos)), "exato"

    # Camada 2: prefixo de categoria no estoque ('HERBICIDA ' + nome do mapa).
    # Exige limite de palavra para 'BORAL 20L' não casar com 'X SUPERBORAL 20L'.
    sufixo = sorted({
        cod for cod, nome_f in fonte_norm
        if nome_f.endswith(alvo) and (len(nome_f) == len(alvo)
                                      or nome_f[-len(alvo) - 1] == " ")
    })
    if sufixo:
        return sufixo, "sufixo"

    contem = sorted({cod for cod, nome_f in fonte_norm if alvo in nome_f})
    if contem:
        return contem, "contem"

    return [], None


def executar(conn, fonte: list, aplicar: bool, forcar: bool) -> dict:
    """Roda o backfill. Sem `aplicar`, nada é escrito."""
    produtos = conn.execute(
        "SELECT produto_id, nome, codigo FROM mapa_produtos ORDER BY nome"
    ).fetchall()

    fonte_norm = [(cod, norm_nome(nome)) for cod, nome in fonte]
    indice_exato = defaultdict(list)
    for cod, nome_n in fonte_norm:
        indice_exato[nome_n].append(cod)
    nome_por_codigo = {cod: nome for cod, nome in fonte}

    casados, ambiguos, nao_encontrados, ja_tinham, conflitos = [], [], [], [], []
    escritas = []
    # Códigos já em uso no mapa: o índice único é global, então o backfill
    # precisa respeitá-lo antes de propor qualquer escrita.
    em_uso = {
        norm_codigo(c): (pid, nome)
        for pid, nome, c in produtos if norm_codigo(c)
    }

    for pid, nome, cod_atual in produtos:
        cod_atual_n = norm_codigo(cod_atual)
        if cod_atual_n and not forcar:
            ja_tinham.append((nome, cod_atual_n))
            continue

        candidatos, camada = casar(nome, indice_exato, fonte_norm)

        if not candidatos:
            nao_encontrados.append(nome)
            continue
        if len(candidatos) > 1:
            ambiguos.append((nome, camada, [
                (c, nome_por_codigo.get(c, "")) for c in candidatos[:6]
            ]))
            continue

        novo = candidatos[0]
        if novo == cod_atual_n:
            ja_tinham.append((nome, cod_atual_n))
            continue

        dono = em_uso.get(novo)
        if dono and dono[0] != pid:
            conflitos.append((nome, novo, dono[1]))
            continue

        casados.append((nome, novo, nome_por_codigo.get(novo, ""), camada,
                        cod_atual_n))
        escritas.append((novo, pid))
        em_uso[novo] = (pid, nome)
        if cod_atual_n:
            em_uso.pop(cod_atual_n, None)

    if escritas and aplicar:
        # Turso embedded replica: cada escrita é round-trip de rede, então
        # o UPDATE vai em lote único em vez de um por produto.
        conn.executemany(
            "UPDATE mapa_produtos SET codigo = ? WHERE produto_id = ?", escritas
        )
        conn.commit()
        try:
            conn.sync()
        except Exception:
            pass

    return {
        "casados": casados, "ambiguos": ambiguos,
        "nao_encontrados": nao_encontrados, "ja_tinham": ja_tinham,
        "conflitos": conflitos, "escritas": len(escritas),
        "total_mapa": len(produtos),
    }


# ── Diagnóstico de órfãos ─────────────────────────────────────────────────────

def relatar_orfaos(conn):
    """Produtos do mapa que não casam com estoque_mestre pelo nome (passo 0)."""
    rows = conn.execute("""
        SELECT mp.nome AS nome_mapa
        FROM mapa_produtos mp
        LEFT JOIN estoque_mestre em
          ON LOWER(TRIM(em.produto)) = LOWER(TRIM(mp.nome))
        WHERE em.produto IS NULL
        ORDER BY mp.nome
    """).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM mapa_produtos").fetchone()[0]
    print(f"\n── Órfãos: {len(rows)} de {total} produto(s) do mapa não casam "
          f"com estoque_mestre por nome ──")
    for (nome,) in rows:
        print(f"  · {nome}")
    return rows


# ── Relatório ─────────────────────────────────────────────────────────────────

def imprimir_relatorio(res: dict, aplicar: bool):
    modo = "APLICADO" if aplicar else "DRY-RUN (nada foi escrito)"
    print(f"\n{'=' * 72}\nBACKFILL mapa_produtos.codigo — {modo}\n{'=' * 72}")

    print(f"\n── Casados: {len(res['casados'])} ──")
    for nome, cod, nome_fonte, camada, antigo in res["casados"]:
        antes = f" (era {antigo})" if antigo else ""
        print(f"  ✓ {nome}{antes}\n      → {cod}  [{camada}]  {nome_fonte}")

    print(f"\n── Ambíguos (não escritos): {len(res['ambiguos'])} ──")
    for nome, camada, cands in res["ambiguos"]:
        print(f"  ? {nome}  [{camada}] — {len(cands)} candidato(s):")
        for cod, nome_fonte in cands:
            print(f"      {cod}  {nome_fonte}")

    print(f"\n── Não encontrados: {len(res['nao_encontrados'])} ──")
    for nome in res["nao_encontrados"]:
        print(f"  ✗ {nome}")

    if res["conflitos"]:
        print(f"\n── Conflito de código único (não escritos): "
              f"{len(res['conflitos'])} ──")
        for nome, cod, dono in res["conflitos"]:
            print(f"  ! {nome} → {cod} já pertence a '{dono}'")

    print(f"\n── Já tinham código (preservados): {len(res['ja_tinham'])} ──")
    for nome, cod in res["ja_tinham"]:
        print(f"  · {nome} = {cod}")

    print(f"\n{'-' * 72}")
    print(f"Total no mapa: {res['total_mapa']} | casados: {len(res['casados'])} "
          f"| ambíguos: {len(res['ambiguos'])} | não encontrados: "
          f"{len(res['nao_encontrados'])} | conflitos: {len(res['conflitos'])} "
          f"| já tinham: {len(res['ja_tinham'])}")
    if aplicar:
        print(f"Linhas atualizadas: {res['escritas']}")
    else:
        print(f"Seriam atualizadas: {res['escritas']}  → rode com --apply "
              f"para gravar")
    print("-" * 72)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Preenche mapa_produtos.codigo casando por nome normalizado.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--apply", action="store_true",
                    help="grava de fato (o padrão é dry-run)")
    ap.add_argument("--force", action="store_true",
                    help="sobrescreve código já preenchido")
    ap.add_argument("--source", choices=("estoque", "xlsx"), default="estoque",
                    help="fonte dos códigos (padrão: estoque_mestre)")
    ap.add_argument("--xlsx", default=os.path.join(_AQUI, "produtos_CAMDA.xlsx"),
                    help="planilha usada com --source xlsx")
    ap.add_argument("--orfaos", action="store_true",
                    help="só imprime o diagnóstico de órfãos e sai")
    args = ap.parse_args(argv)

    conn = conectar()

    if args.orfaos:
        checar_tabelas(conn)
        relatar_orfaos(conn)
        return 0

    checar_tabelas(conn)
    if args.source == "xlsx":
        fonte = carregar_do_xlsx(args.xlsx)
        print(f"→ fonte: {args.xlsx} ({len(fonte)} produto(s) com código)")
    else:
        fonte = carregar_do_estoque(conn)
        print(f"→ fonte: estoque_mestre ({len(fonte)} produto(s) com código)")

    if not fonte:
        print("ERRO: a fonte não tem nenhum produto com código.", file=sys.stderr)
        return 1

    relatar_orfaos(conn)
    res = executar(conn, fonte, aplicar=args.apply, forcar=args.force)
    imprimir_relatorio(res, args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
