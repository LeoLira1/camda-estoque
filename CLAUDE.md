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
   credenciais do Turso de PRODUÇÃO. O arquivo **não é mais versionado**
   (saiu do índice do git; `.gitignore` linha 20 agora vale), então não há
   mais o risco de commitá-lo por engano. Para testar sem tocar no banco
   compartilhado: mova o `secrets.toml` para fora temporariamente (o app cai
   em modo local) e semeie o `camda_local.db` com algumas linhas em
   `estoque_mestre` (o dashboard só renderiza se `has_mestre > 0`). Nunca
   combine as credenciais reais com um `camda_local.db` já existente: dá
   `sync error: invalid local state: db file exists but metadata file does
   not` — apague `camda_local.db*` nesse caso.

4. **Login e overlay de calendário.** As senhas não ficam no código: vêm dos
   secrets `CAMDA_ACCESS_PASSWORD` (acesso) e `CAMDA_EDIT_PASSWORD` (edição).
   Ao mover o `secrets.toml` para fora (item 3) o login para de funcionar —
   exporte as duas como variáveis de ambiente, ou coloque-as num `.env`
   local (também ignorado pelo git), que o `load_dotenv()` carrega. Sem elas
   a tela de login mostra "senha não configurada" e ninguém entra.
   Após o login, o popup de calendário `#camda-cal-overlay` intercepta TODOS
   os cliques no Playwright — remova-o com
   `page.evaluate("document.getElementById('camda-cal-overlay')?.remove()")`
   após o login e após cada rerun, antes de clicar em qualquer coisa.

5. **Instalação.** `streamlit` não vem instalado: use
   `pip install -r requirements.txt` (streamlit==1.59.0). Playwright: use o
   Chromium pré-instalado (`executablePath: /opt/pw-browsers/chromium`) e
   nunca rode `playwright install`. O import do banco é `import libsql`
   (não `libsql_experimental`).

6. **Esperas no teste E2E.** O primeiro carregamento do dashboard com caches
   frios demora (>9s): faça polling pelos elementos (ex.:
   `div.st-key-dash_nav button`) em vez de `wait_for_timeout` fixo. Critério
   de sucesso: uma pill por entrada de `_DASH_TABS` (**hoje são 20**, não 19 —
   confira a lista em vez de fixar o número) E zero
   `[data-testid="stException"]`. Cuidado com falso "PASS" quando a página
   nem chegou a carregar (0 pills ⇒ 0 exceções).

7. **Seletores de widget no Playwright (streamlit 1.59).** `st.pills` e
   `st.radio` renderizam DIFERENTE, e trocar um pelo outro dá 0 elementos
   sem erro nenhum:
   - `st.pills` → `button[role="radio"]`, sem `<input>`.
   - `st.radio` → `label[data-testid="stRadioOption"]` com um
     `input[type=radio]` escondido dentro; a opção **não** tem
     `role="radio"`. O `<label>` do rótulo do widget também conta em
     `label`, então contar `label` dá n+1.

   Duas outras pegadinhas: `div.st-key-<key>` aparece primeiro contendo só
   um `[data-testid="stSkeleton"]` — espere pelo widget de dentro, não pelo
   container, senão você inspeciona o esqueleto. E a `.camda-topbar` (além
   do overlay do item 4) intercepta cliques: use `click(force=True)`.

8. **`pdfplumber` não importa neste sandbox — conserte com `cffi`.** O import
   morre com `pyo3_runtime.PanicException: Python API call failed` vindo do
   `cryptography` do sistema, e o mesmo derruba `pypdf`. A causa **não** é o
   `cryptography`: é o `_cffi_backend` que falta. `pip install cffi` resolve e
   destrava os dois (não tente reinstalar o `cryptography` — ele vem do
   Debian, sem RECORD, e o pip se recusa a desinstalar). Nada disso é problema
   do app: no Streamlit Cloud o parser MATR480 roda normalmente.

   Se por algum motivo o `cffi` não colar, o plano B para contar páginas de um
   PDF é ler a estrutura: `/Type /Page` e `/Count` nos bytes do arquivo.

## Estrutura do dashboard

- A navegação principal usa `st.pills` (key=`dash_nav`) com renderização
  condicional: só o bloco `if _dash_tab == _TAB_X:` da aba ativa executa.
  Não converta de volta para `st.tabs` — ele renderiza todas as abas de
  `_DASH_TABS` em todo rerun e foi a causa da lentidão original.
- Labels das abas ficam estáticas (sem contadores) para não invalidar o
  widget entre reruns.
- O expander "📤 Upload de Planilha" é um bloco `with` no nível do módulo:
  código de aba colocado depois dele por engano renderiza DENTRO do
  expander. Novas abas devem ficar dentro de `if has_mestre:`, antes da
  seção de Upload.
- A aba 🏷️ Etiquetas (`etiquetas_tab.py`) não gera PDF: monta um HTML
  autocontido que o usuário imprime com Ctrl+P (o A4 vem do `@page` do CSS).
  Os tamanhos de etiqueta ficam no dict `_PRESETS` — um tamanho novo é uma
  entrada nova ali, sem mexer em renderização. QR pelo `segno`, codificando
  só o código do produto.
- A aba 🔄 Inv. Cíclico tem DUAS fontes para a contagem: `estoque_mestre`
  (`status_ciclo`/`contado_ciclo_em`, a conferência *válida*) e o histórico
  `inventario_cicli` (a contagem *física*, que nunca é apagada). Todo upload de
  planilha que muda `qtd_sistema` de um item conferido zera as colunas de
  `estoque_mestre` — o item volta a "pendente". Por isso a data que aparece no
  card pendente e no modal vem do histórico (`_get_ultimas_contagens_cicli`),
  não de `estoque_mestre`: é ela que preserva a janela de auditoria (há quantos
  dias ninguém olha aquele produto na prateleira). Não troque essa origem pela
  coluna de `estoque_mestre` "para simplificar" — some de novo a cada venda.
- **Nunca mande uma lista inteira num único `st.markdown`.** Acima de 10 000
  bytes (`global.minCachedMessageSize`) o Streamlit marca o ForwardMsg como
  *cacheable*: na segunda vez que aquele conteúdo aparece na sessão o servidor
  envia só o `ref_hash` e o navegador tem de resolver pelo cache dele. Se o
  navegador já descartou o hash (aba restaurada, celular sob pressão de
  memória, segunda aba), o elemento chega VAZIO — sem erro, sem exceção. Foi
  assim que a lista da aba 📋 Hist. Contagem sumiu enquanto os KPIs ("33
  contados") e os títulos, pequenos demais para cachear, continuavam na tela.
  O `_render_rows()` do `historico_contagem_tab.py` é o padrão a copiar:
  quebra as linhas em blocos de ~6 KB dentro de um `st.container(key=...)`
  cujo CSS zera o `gap` E as margens do markdown (só zerar o gap faz as linhas
  se sobreporem 13px). Vale para qualquer lista longa em HTML cru.
- O campo de busca do header (key=`search_mestre`) é sobreposto ao topbar
  via CSS com paddings que reservam as zonas laterais (marca à esquerda,
  resumo operacional à direita) — breakpoints em 980px e 720px. Se mudar o
  conteúdo do header, reveja esses paddings.
