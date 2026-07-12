# CAMDA Estoque — instruções para Claude Code

App Streamlit de arquivo único (`app_turso.py`, ~13,7 mil linhas) com banco
Turso/libSQL (réplica local embarcada + sync na nuvem). Deploy no Streamlit
Cloud. Streamlit fixado em 1.59.0 — não atualize sem testar.

## Ambiente de teste local — armadilhas conhecidas (leia ANTES de rodar o app)

Estas falhas já aconteceram em sessões anteriores; aplique as correções de
antemão em vez de redescobri-las:

1. **pandas 3.x causa segfault.** O sandbox costuma vir com pandas 3.x, que
   derruba o servidor com "Segmentation fault" (crash nativo em
   `string_arrow._from_sequence` ao construir DataFrames, disparado via
   `get_materiais_terceiros`). Depois do `pip install -r requirements.txt`,
   garanta `pip install "pandas>=2.2,<3"`. Sintoma: navegador mostra
   "Connection error" e o processo morre sem traceback no log.

2. **Servidor em background morre entre chamadas de shell.** O sandbox mata
   processos iniciados com `&`/`nohup` em invocações anteriores do Bash.
   Inicie o `streamlit run` e execute o teste Playwright **na mesma
   invocação de shell**, finalizando com `kill $SPID`. Use loop de retry
   com restart do servidor — o teste é flaky se o item 1 não foi corrigido.

3. **Credenciais reais em `.streamlit/secrets.toml`.** O ambiente injeta
   credenciais do Turso de PRODUÇÃO. Para testar sem tocar no banco
   compartilhado: mova o `secrets.toml` para fora temporariamente (o app cai
   em modo local), semeie o `camda_local.db` com algumas linhas em
   `estoque_mestre` (o dashboard só renderiza se `has_mestre > 0`) e
   **restaure o `secrets.toml` antes de commitar**. Nunca combine as
   credenciais reais com um `camda_local.db` já existente: dá
   `sync error: invalid local state: db file exists but metadata file does
   not` — apague `camda_local.db*` nesse caso.

4. **Login e overlay de calendário.** Senha de acesso: `força` (senha de
   edição: padrão `camda@edit`). Após o login, o popup de calendário
   `#camda-cal-overlay` intercepta TODOS os cliques no Playwright —
   remova-o com
   `page.evaluate("document.getElementById('camda-cal-overlay')?.remove()")`
   após o login e após cada rerun, antes de clicar em qualquer coisa.

5. **Instalação.** `streamlit` não vem instalado: use
   `pip install -r requirements.txt` (streamlit==1.59.0). Playwright: use o
   Chromium pré-instalado (`executablePath: /opt/pw-browsers/chromium`) e
   nunca rode `playwright install`. O import do banco é `import libsql`
   (não `libsql_experimental`).

6. **Esperas no teste E2E.** O primeiro carregamento do dashboard com caches
   frios demora (>9s): faça polling pelos elementos (ex.:
   `div.st-key-dash_nav button`, que deve ter 19 pills) em vez de
   `wait_for_timeout` fixo. Critério de sucesso: 19 pills presentes E zero
   `[data-testid="stException"]`. Cuidado com falso "PASS" quando a página
   nem chegou a carregar (0 pills ⇒ 0 exceções).

## Estrutura do dashboard

- A navegação principal usa `st.pills` (key=`dash_nav`) com renderização
  condicional: só o bloco `if _dash_tab == _TAB_X:` da aba ativa executa.
  Não converta de volta para `st.tabs` — ele renderiza as 19 abas em todo
  rerun e foi a causa da lentidão original.
- Labels das abas ficam estáticas (sem contadores) para não invalidar o
  widget entre reruns.
- O expander "📤 Upload de Planilha" é um bloco `with` no nível do módulo:
  código de aba colocado depois dele por engano renderiza DENTRO do
  expander. Novas abas devem ficar dentro de `if has_mestre:`, antes da
  seção de Upload.
- O campo de busca do header (key=`search_mestre`) é sobreposto ao topbar
  via CSS com paddings que reservam as zonas laterais (marca à esquerda,
  resumo operacional à direita) — breakpoints em 980px e 720px. Se mudar o
  conteúdo do header, reveja esses paddings.
