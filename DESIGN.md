---
name: CAMDA Estoque
description: Dashboard operacional de inventário agrícola — instrumento de precisão enraizado no cerrado brasileiro.
colors:
  verde-cerrado: "#00d68f"
  verde-cerrado-deep: "#00b887"
  azul-referencia: "#3b82f6"
  vermelho-falta: "#ff4757"
  ambar-sobra: "#ffa502"
  roxo-viz: "#a55eea"
  ciano-prazo: "#00c4ff"
  noite-cerrado: "#0a0f1a"
  superficie: "#111827"
  superficie-elevada: "#1a2332"
  borda-superficie: "#1e293b"
  texto-primario: "#e0e6ed"
  texto-secundario: "#7bafd4"
  texto-mudo: "#64748b"
  texto-desabilitado: "#4a5568"
typography:
  display:
    fontFamily: "Outfit, sans-serif"
    fontSize: "2rem"
    fontWeight: 900
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Outfit, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.25
  title:
    fontFamily: "Outfit, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "JetBrains Mono, monospace"
    fontSize: "0.75rem"
    fontWeight: 700
    letterSpacing: "0.06em"
rounded:
  sm: "8px"
  md: "10px"
  lg: "12px"
  xl: "20px"
  pill: "28px"
spacing:
  xs: "6px"
  sm: "8px"
  md: "16px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.verde-cerrado}"
    textColor: "{colors.noite-cerrado}"
    rounded: "{rounded.sm}"
    padding: "10px 20px"
    typography: "{typography.label}"
  button-primary-hover:
    backgroundColor: "{colors.verde-cerrado-deep}"
    textColor: "{colors.noite-cerrado}"
  button-ghost:
    textColor: "{colors.texto-primario}"
    rounded: "{rounded.sm}"
    padding: "8px 16px"
  badge-ok:
    textColor: "{colors.verde-cerrado}"
    rounded: "{rounded.sm}"
    padding: "2px 8px"
    typography: "{typography.label}"
  badge-falta:
    textColor: "{colors.vermelho-falta}"
    rounded: "{rounded.sm}"
    padding: "2px 8px"
    typography: "{typography.label}"
  badge-sobra:
    textColor: "{colors.ambar-sobra}"
    rounded: "{rounded.sm}"
    padding: "2px 8px"
    typography: "{typography.label}"
  card-tonal:
    backgroundColor: "{colors.superficie}"
    rounded: "{rounded.lg}"
    padding: "{spacing.md}"
  input-default:
    backgroundColor: "{colors.superficie-elevada}"
    rounded: "{rounded.sm}"
    padding: "8px 12px"
---

# Design System: CAMDA Estoque

## 1. Overview: O Terminal do Cerrado

**Creative North Star: "O Terminal do Cerrado"**

CAMDA Estoque é um instrumento de operação — não um produto de marketing, não um dashboard genérico de SaaS. A interface existe para um único usuário experiente que conhece profundamente os dados que está vendo: quantidades, códigos de produto, datas de vencimento, divergências de inventário. A partir dessa premissa, cada decisão visual tem uma pergunta de teste: *isso serve ao trabalho, ou serve à aparência?* Se a resposta for aparência, o elemento está errado.

A identidade visual é enraizada no agronegócio do Brasil Central — não de forma literal (sem ícones de trator, sem paletas terrosas decorativas), mas na escolha de um verde que é operacional antes de ser bonito, num contraste alto que funciona sob luz de escritório, numa tipografia monoespacial que trata número como dado antes de tratá-lo como texto. O sistema rejeita a estética "dark SaaS genérico": o azul-marinho monótono do Grafana, a grade de cards idênticos sem identidade de setor, o template que poderia pertencer a qualquer startup de fintech ou DevOps. Este produto gerencia soja, milho, defensivos e adubos de uma cooperativa real no Goiás — deve ser reconhecível como tal.

A filosofia de densidade é intencional: **denso mas navegável**. O usuário precisa processar muita informação por sessão — status de centenas de produtos, datas críticas, quantidades divergentes. O sistema não reduz a carga escondendo informação; organiza com hierarquia tipográfica, agrupamento semântico e cor com propósito. Whitespace generoso seria mentira de conforto em uma ferramenta de alta carga operacional.

**Key Characteristics:**
- Tema escuro permanente: alta densidade em ambiente de escritório, sessões longas
- Verde Cerrado (`#00d68f`) como linguagem operacional — sinaliza OK, não decora
- Três vozes tipográficas com papéis rígidos: Outfit (títulos) / DM Sans (corpo) / JetBrains Mono (dados)
- Status codificados por cor com espaço visual garantido — alertas nunca são apenas um ícone discreto
- Elevação via layering tonal; blur (`backdrop-filter`) restrito a elementos flutuantes
- Responsive: compacto em ≤640px, grid operacional em ≥641px

## 2. Colors: A Paleta do Cerrado

Paleta operacional de quatro funções: fundo profundo / superfícies escalonadas / semântica de status / texto em três níveis de ênfase. Cada cor tem um papel; usar fora dele é romper a linguagem visual.

### Primary

- **Verde Cerrado** (`#00d68f`): A cor operacional central. Sinaliza estado OK, confirma ações, destaca o count principal no dashboard. Nunca decorativo — quando aparece, responde à pergunta "o que está aprovado ou ativo aqui?". Gradiente com Verde Cerrado Deep (`#00b887`) em botões primários e destaques de KPI.
- **Verde Cerrado Deep** (`#00b887`): Variante de hover/pressão do verde primário. Também o ponto final de gradientes de destaque.

### Secondary

- **Azul Referência** (`#3b82f6`): Códigos de produto, links, referências do sistema (nota fiscal, nome do cooperado). Indica "dado recuperável de outro lugar" — distinto do verde que indica "estado atual aqui". Usado também no glow de tab ativa.

### Tertiary

- **Roxo Viz** (`#a55eea`): Restrito a visualizações de dados (treemaps, gráficos, segmentos de análise). Proibido em UI funcional — botões, badges, indicadores de estado.
- **Ciano Prazo** (`#00c4ff`): Restrito a alertas de prazo e validade (faixa ≤90 dias). Distingue urgência de prazo (ciano → âmbar → vermelho) de ruptura de estoque (vermelho direto).

### Status (semântico — não intercambiável)

- **Vermelho Falta** (`#ff4757`): Ruptura de estoque, item em falta, divergência crítica. Exige espaço visual real — não apenas badge na borda.
- **Âmbar Sobra** (`#ffa502`): Excesso de estoque, aviso de atenção, validade próxima (≤30d). Exige espaço visual real.

### Neutral

- **Noite do Cerrado** (`#0a0f1a`): Fundo da aplicação. Nunca `#000000` puro — o azul residual ancora a identidade noturna.
- **Superfície** (`#111827`): Cards, containers, painéis — primeira camada acima do fundo.
- **Superfície Elevada** (`#1a2332`): Segunda camada (headers de seção, campos de input, áreas ativas).
- **Borda de Superfície** (`#1e293b`): Bordas de cards e divisores. Um contorno sutil — estrutura sem ruído visual.
- **Texto Primário** (`#e0e6ed`): Corpo de texto, labels, valores de dado. Tom frio intencional — não branco puro.
- **Texto Secundário** (`#7bafd4`): Texto auxiliar, metadados, timestamps, tabs inativas no hover. **Restrito a texto** — não usar como cor de borda de glass ou glow de fundo.
- **Texto Mudo** (`#64748b`): Placeholders, estados desabilitados, texto de apoio de baixa hierarquia.
- **Texto Desabilitado** (`#4a5568`): Elementos inativos, controles bloqueados.

### Named Rules

**A Regra do Verde Operacional.** Cada uso de `#00d68f` na tela responde à pergunta: "o que está OK aqui?" Se a resposta for vaga ou nenhuma, a cor está errada. Verde como decoração quebra a linguagem semântica do sistema.

**A Regra do Espaço Real.** Alertas de vencimento e ruptura nunca são silenciosos — nunca apenas um ícone discreto na borda de um card ou uma badge de 16px no canto. Vermelho Falta e Âmbar Sobra exigem área visual dedicada: banner, linha de tabela colorida, card completo, número em Display. Se o alerta couber em 16px, não é suficiente.

**A Regra do Texto Secundário.** `#7bafd4` existe como cor de texto auxiliar. Seu azul saturado é forte demais para bordas e glows — esses usam Borda de Superfície (`#1e293b`) ou transparências de branco baixas. Misturar os dois papéis polui a hierarquia visual.

## 3. Typography: Três Vozes, Uma Hierarquia

**Display / Headline / Title Font:** Outfit (variável, Google Fonts — pesos 300, 500, 700, 900)
**Body Font:** DM Sans (Google Fonts — pesos 300, 400, 500, 600)
**Data Font:** JetBrains Mono (Google Fonts / JetBrains — pesos 400, 700)

**Character:** Outfit traz autoridade estrutural em títulos — weight 900 para KPIs de alto impacto, 700 para seções, 600 para subtítulos. DM Sans sustenta texto denso sem fadiga visual: humanist, x-height alto, legível em corpo pequeno. JetBrains Mono não é "apenas monospace" — foi projetada para leitura de dados em sessões longas: alinhamento numérico perfeito em colunas, dígitos uniformes, diferenciação clara entre 0/O e l/1.

### Hierarchy

- **Display** (Outfit 900, 2rem / 32px, line-height 1.1, tracking −0.02em): KPIs e grandes contagens no dashboard. Reservado para o número principal de uma tela — nunca mais de um por seção visível.
- **Headline** (Outfit 700, 1.25rem / 20px, line-height 1.25): Títulos de seção, headers de modal, nome de tab ativa.
- **Title** (Outfit 600, 1rem / 16px, line-height 1.4): Card titles, labels de grupo, subtítulos de painel, rótulos de formulário.
- **Body** (DM Sans 400, 0.875rem / 14px, line-height 1.6): Texto corrido, descrições, mensagens de estado vazio. Em blocos de prose, limite de linha: 65ch.
- **Label** (JetBrains Mono 700, 0.75rem / 12px, tracking 0.06em, uppercase): Códigos de produto, quantidades em tabelas, status badges, timestamps, unidades de medida. Todo dado que é escaneado mais do que lido.

### Named Rules

**A Regra do Monoespaciado.** Qualquer valor numérico operacional — quantidade em estoque, código de produto, data de vencimento, preço de insumo — usa JetBrains Mono. Números em Outfit ou DM Sans são decoração; em Mono são dados. A distinção é funcional: colunas alinhadas à direita, leitura de dígito a dígito, sem ambiguidade tipográfica.

**A Fonte Syne está eliminada.** O código-fonte importa Syne como fonte alternativa de heading. Ela não faz parte deste sistema — Outfit é a única fonte de título. Syne não deve aparecer em nenhum novo componente ou screen. Consistência de tipo é mais valiosa que variedade de estilo.

## 4. Elevation: Tonal por Padrão, Blur Reservado

O sistema usa **layering tonal** como estratégia primária de profundidade: Noite do Cerrado (`#0a0f1a`) → Superfície (`#111827`) → Superfície Elevada (`#1a2332`). Três níveis são suficientes para qualquer hierarquia de interface.

**`backdrop-filter: blur()` é recurso reservado.** Aplicado apenas em elementos que flutuam sobre o conteúdo existente: modais/dialogs, tooltips, popovers, sheets de ação móvel. Cards de conteúdo, painéis de dados, grids de inventário, tabs de navegação — todos usam background tonal sólido com borda de 1px.

> **Divergência com o código atual:** O app hoje aplica `backdrop-filter` amplamente em tabs (`rgba(255,255,255,0.04)` com `rgba(255,255,255,0.08)` de borda) e em alguns cards. A migração para layering tonal nesses elementos é a mudança estrutural mais importante do spec. Elementos flutuantes (modais `st.dialog()`) mantêm o blur.

### Shadow Vocabulary

- **Sombra Flutuante** (`0 24px 64px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.08)`): Modais e dialogs — qualquer elemento que flutua sobre o conteúdo. Sombra profunda + highlight interno sutil.
- **Sombra de Hover** (`0 4px 16px rgba(0,214,143,0.15)`): Cards clicáveis no estado hover. Glow verde intencional — indica interatividade sem esconder conteúdo.
- **Focus Ring** (`0 0 0 2px rgba(0,214,143,0.4)`): Focus ring de acessibilidade em inputs, botões e elementos focáveis via teclado. Mesmo verde, mas como outline, não como sombra.

### Named Rules

**A Regra do Vidro Reservado.** Quando tudo tem blur, nada tem profundidade. `backdrop-filter` é um recurso caro — visualmente e em performance. Cards tonais são o padrão; blur é a exceção que sinaliza "este elemento está acima de tudo o mais". Usar blur em cards de inventário nivela o que deveria ter hierarquia.

## 5. Components: Denso mas Navegável

Cada componente resolve uma pergunta operacional específica. A filosofia é "denso mas navegável": informação comprimida sem parecer caos. Componentes não existem para impressionar; existem para responder perguntas rápido.

### Buttons

Ações, não decoração. Arredondamento moderado, tamanho proporcional à importância da ação.

- **Shape:** Arredondado suave (8px — `rounded.sm`). Pill (28px) apenas em ações flutuantes de contexto (ex: FAB em mobile) — proibido em botões de formulário.
- **Primary:** Verde Cerrado (`#00d68f`) com texto Noite do Cerrado (`#0a0f1a`). Padding 10px 20px. JetBrains Mono 700 uppercase, tracking 0.06em. A cor escura no texto garante contraste com o verde brilhante.
- **Hover:** Verde Cerrado Deep (`#00b887`), scale 1.02, transition 150ms ease-out. Focus ring 2px verde.
- **Ghost / Secundário:** Borda 1px `#1e293b`, texto Texto Primário, sem background. Hover adiciona Superfície Elevada como fundo. Para ações de baixa hierarquia.

### Chips / Badges de Status

A linguagem visual mais crítica do sistema — traduzem estado de inventário em informação instantânea.

- **Style:** Background tintado (12% de opacidade da cor de status sobre Superfície), texto na cor plena, JetBrains Mono 700 uppercase tracking 0.08em, tamanho 0.6rem, padding 2px 8px, radius 8px.
- **Variants:** `badge-ok` (Verde Cerrado), `badge-falta` (Vermelho Falta), `badge-sobra` (Âmbar Sobra), `badge-avaria` (`#ff6b7a` — variante mais suave do vermelho para danos físicos).
- **Proibido:** Badge com apenas ícone. Sempre texto + cor. "FALTA" em vermelho carrega mais informação que um círculo vermelho — o texto é parte da semântica, não redundância.

### Cards / Containers

- **Corner Style:** Arredondado (10–12px — `rounded.md` / `rounded.lg`) — curva presente mas não dominante.
- **Background:** Superfície (`#111827`) — background tonal sólido, sem blur.
- **Shadow Strategy:** Flat por padrão; Sombra de Hover (`0 4px 16px rgba(0,214,143,0.15)`) em cards clicáveis.
- **Border:** Borda de Superfície (`#1e293b`), 1px — define o contorno no fundo escuro sem peso excessivo.
- **Internal Padding:** 16px (`spacing.md`) padrão; 10–12px em grids de alta densidade.

### Inputs / Fields

- **Style:** Background Superfície Elevada (`#1a2332`), borda 1px `#1e293b`, radius 8px.
- **Focus:** Borda verde (`#00d68f`), glow `0 0 0 2px rgba(0,214,143,0.25)`, transition 200ms.
- **Error:** Borda Vermelho Falta (`#ff4757`), sem glow — erro é estado, não ênfase visual.
- **Placeholder:** Texto Mudo (`#64748b`).
- **Disabled:** Opacidade 40%, cursor not-allowed.

### Navigation (Tabs)

- **Style:** Background Superfície Elevada tonal (`#1a2332`), borda 1px `#1e293b`, radius 10px.
- **Active:** Background ligeiramente mais claro (`rgba(59,130,246,0.12)`), borda Azul Referência (`rgba(59,130,246,0.40)`), texto Texto Primário peso 600. Glow sutil em azul.
- **Inactive:** Texto Mudo (`#64748b`), peso 400. Hover → Texto Secundário (`#7bafd4`).
- **Mobile:** Overflow-x: auto com scrollbar invisível — nunca truncar label de tab.
- **Divergência atual:** O código usa `rgba(123,175,212,...)` (Texto Secundário) como cor de borda e glow de tab ativa. O spec migra para Azul Referência (`#3b82f6`) que tem papel semântico claro no sistema.

### Stat Card (Componente Assinatura)

O componente mais característico do sistema — KPI de alto impacto em dois elementos: número e contexto.

- **Layout:** Stack vertical centralizado. Dado em Display (JetBrains Mono, 2rem, 900), label em Label (JetBrains Mono 700 uppercase, 0.55–0.65rem, Texto Mudo).
- **Background:** Card Tonal — Superfície (`#111827`), 12px radius, 16px padding.
- **Accent Line:** Borda superior 2px na cor semântica do KPI (Verde para count OK, Vermelho para falta, Âmbar para sobra). Indica imediatamente o caráter do número antes de ler o label.
- **Proibido:** Ícone decorativo ao lado do número. O número é o elemento visual principal — ícones são ruído em StatCards.

### Alert Banner (Componente Crítico)

Implementação concreta da Regra do Espaço Real.

- **Layout:** Flex row — número grande (Display, cor de status) + coluna de texto (Title + Label).
- **Background:** 10% de opacidade da cor de status. Borda 1px a 30% de opacidade.
- **Propósito:** Ruptura ou vencimento crítico visível imediatamente ao abrir o dashboard — sem precisar escanear listas. O número em Display é o primeiro elemento que o olho encontra.

## 6. Do's and Don'ts

### Do:

- **Use Verde Cerrado como linguagem semântica.** Cada `#00d68f` na tela responde a "o que está OK aqui?". Se a resposta for vaga, remova a cor.
- **Use JetBrains Mono para todo dado numérico operacional.** Quantidade em estoque, código de produto, data de vencimento, preço de insumo — todos em Mono. Números em sans-serif são decoração; em Mono são dados.
- **Dê espaço visual real a alertas críticos.** Vermelho Falta e Âmbar Sobra exigem área dedicada — banner, card completo, número em Display. Nunca apenas badge discreta na borda de outro elemento.
- **Mantenha blur restrito a elementos flutuantes.** `backdrop-filter: blur()` apenas em modais (`st.dialog()`), tooltips, popovers. Cards de inventário, tabs e painéis usam layering tonal sólido.
- **Use a escala Noite do Cerrado → Superfície → Superfície Elevada para profundidade.** Três níveis tonais substituem sombras em 90% dos casos.
- **Mantenha badges com texto + cor.** "FALTA" em vermelho é mais informativo que um ícone vermelho — o texto é parte da semântica.
- **Limit card grids a variações de conteúdo, não de shape.** Cards de inventário têm o mesmo formato; o que varia é o conteúdo e o status. Evitar grids onde cada card tem layout próprio.

### Don't:

- **Não use glassmorfismo em cards de conteúdo.** `backdrop-filter: blur()` em cards de inventário, listas de produto, grids de dados ou tabs de navegação é anti-padrão neste sistema — viola a Regra do Vidro Reservado e polui a hierarquia de profundidade.
- **Não crie dashboards estilo Grafana/Datadog** — azul-marinho monótono, grade de cards idênticos, nenhuma identidade de setor. Este produto é inventário agrícola no cerrado; deve ser impossível de confundir com uma ferramenta de observabilidade ou DevOps.
- **Não use rainbow charts estilo PowerBI/Tableau** — múltiplos gráficos com paletas independentes na mesma tela. Visualizações seguem a paleta semântica do sistema.
- **Não use whitespace excessivo estilo Notion.** Esta é uma ferramenta de alta densidade operacional. Espaçamento generoso é inadequado quando há centenas de produtos para verificar por sessão.
- **Não use a fonte Syne.** Eliminada do sistema. Outfit é a única fonte de título. Syne não deve aparecer em nenhum novo componente.
- **Não use Texto Secundário (`#7bafd4`) como cor de borda ou glow.** Restrito a texto auxiliar. Bordas usam `#1e293b`; glows usam transparências de verde ou branco.
- **Não hardcode cores de fornecedor como tokens de design.** As cores de FMC, Syngenta, Bayer, Corteva, etc. são dados dinâmicos — geradas algoritmicamente por produto, não hardcoded no CSS como constantes de design.
- **Não crie um template genérico "dark SaaS"** que poderia pertencer a qualquer produto de qualquer setor. Se alguém olhar para a tela e não puder deduzir que é uma ferramenta de cooperativa agrícola, o design falhou o teste de identidade.
