# CAMDA Estoque — Guia de Mudanças e Evolução do App

> Documento de referência para solicitar, registrar e implementar futuras modificações no aplicativo Flutter CAMDA Estoque.

---

## 📱 Estado Atual do App (v1.1)

### Abas disponíveis (navegação)
| Aba | Descrição |
|---|---|
| 🏠 Dashboard | KPIs resumidos: faltas, sobras, avarias, contagem |
| 📦 Estoque | Lista completa com código, cooperado (nota) e status |
| ⚠️ Avarias | Registro e resolução de produtos avariados |
| 📅 Validade | Filtros: Vencidos / ≤7d / ≤30d / ≤60d / ≤90d / OK |
| 🏪 Reposição | Itens para repor com qtd vendida e qtd em estoque |
| 🧾 Lançamentos | Ajustes manuais de estoque |
| ✅ Contagem | Contagem física de produtos |
| 📷 Pendências | Registro fotográfico de pendências de entrega |

### Funcionalidades implementadas
- ✅ Autenticação por senha
- ✅ Busca e filtros em tempo real (estoque)
- ✅ Modo escuro / modo claro (toggle na navegação)
- ✅ Câmera e galeria para pendências de entrega
- ✅ Suporte a tablet e desktop (NavigationRail lateral)
- ✅ Cache offline (estoque)
- ✅ Formatação pt_BR (datas e números)
- ✅ Build automático via GitHub Actions

---

## 🔄 Histórico de Mudanças

### v1.1.0 — 2026-03-15
- Adicionado código do produto na aba Estoque
- Nome do cooperado (campo `nota`) exibido em azul na aba Estoque
- Aba Validade: novos filtros por período (≤7/30/60/90 dias)
- Aba Reposição: exibe código do produto, qtd vendida e qtd em estoque
- Reposição: join com `estoque_mestre` para buscar estoque disponível
- Removidas as abas: Mapa Visual, Vendas, Princípios Ativos
- Implementado toggle de tema claro/escuro
- GitHub Actions: build automático para branches `main` e `claude/**`

### v1.0 — Versão inicial
- Estrutura base com 11 abas
- Tema escuro glassmorphism
- Integração com Turso (libSQL)
- Layout adaptativo mobile/tablet

---

## 📋 Como Solicitar Mudanças

Para solicitar modificações no app, descreva:

1. **Qual aba** deve ser alterada
2. **O que deve mudar** (campo novo, cor, filtro, botão, etc.)
3. **Comportamento esperado** (o que acontece ao clicar/ver)
4. **Dados necessários** (se precisar de novo campo no banco)

### Exemplo de boa solicitação:
> "Na aba Reposição, quero que ao clicar em um item apareça um botão para registrar a quantidade que foi de fato reposta, salvando no banco com data/hora."

---

## 🗺️ Roadmap — Possíveis Melhorias Futuras

### Alta prioridade
- [ ] **Push Notifications** — alertar sobre produtos críticos de validade (< 7 dias)
- [ ] **Offline completo** — cache para todas as telas, não só Estoque
- [ ] **Foto de reposição** — tirar foto ao marcar item como reposto
- [ ] **Filtro por cooperado** — filtrar estoque pelo nome do cooperado responsável
- [ ] **Dashboard melhorado** — gráfico de pizza de status + tendência semanal

### Média prioridade
- [ ] **Busca global** — pesquisar em todas as abas de uma vez
- [ ] **Exportar PDF** — relatório de faltas/sobras em PDF
- [ ] **Histórico de contagem** — ver contagens anteriores por produto
- [ ] **Avarias com foto** — registrar foto do produto avariado
- [ ] **Login biométrico** — usar impressão digital em vez de senha
- [ ] **Multi-usuário** — identificar qual cooperado está logado
- [ ] **Compartilhar pendência** — enviar foto de pendência por WhatsApp/e-mail

### Baixa prioridade
- [ ] **Widget na tela inicial** — exibir resumo do estoque na home do Android
- [ ] **Modo tablet aprimorado** — layout em dois painéis (lista + detalhe)
- [ ] **Tema por cooperativa** — escolher cores primárias do app
- [ ] **Animações de transição** — transições entre abas mais suaves
- [ ] **Atalhos de teclado** — suporte a teclado físico (tablet com teclado)

---

## 🏗️ Arquitetura do App

```
camda-app/lib/
├── core/
│   ├── constants/     # AppConstants (dimensões, timeouts)
│   ├── services/      # CacheService
│   ├── theme/         # AppColors, AppTheme, themeNotifier
│   └── utils/         # DateUtils, NumberUtils
├── data/
│   ├── database/      # TursoClient (HTTP → libSQL)
│   ├── models/        # Produto, Reposicao, ValidadeLote, Avaria...
│   └── repositories/  # EstoqueRepository, ValidadeRepository...
├── features/
│   ├── auth/          # LoginScreen
│   ├── dashboard/     # DashboardScreen
│   ├── estoque/       # EstoqueScreen
│   ├── avarias/       # AvariasScreen
│   ├── validade/      # ValidadeScreen
│   ├── reposicao/     # ReposicaoScreen
│   ├── lancamentos/   # LancamentosScreen
│   ├── contagem/      # ContagemScreen
│   └── pendencias/    # PendenciasScreen
└── shared/
    ├── layouts/       # MainLayout (BottomNav + NavigationRail)
    └── widgets/       # GlassCard, StatCard, LoadingWidget...
```

### Banco de dados (Turso / libSQL)
| Tabela | Uso |
|---|---|
| `estoque_mestre` | Produtos, quantidades, status, nota/cooperado |
| `avarias` | Registro de avarias |
| `validade_lotes` | Lotes com data de vencimento |
| `reposicao_loja` | Itens para repor na loja |
| `pendencias_entrega` | Fotos de pendências (base64) |
| `lancamentos` | Ajustes manuais de estoque |
| `contagem_itens` | Registros de contagem física |

---

## ⚙️ Build e Deploy

### Variáveis de ambiente obrigatórias (GitHub Secrets)
```
TURSO_DATABASE_URL   → URL do banco Turso (libsql://...)
TURSO_AUTH_TOKEN     → Token JWT de autenticação
CAMDA_PASSWORD       → Senha de acesso ao app
```

### Fluxo de build automático
```
Push para main        → Build APK + GitHub Release oficial
Push para claude/**   → Build APK + Artifact (pré-release)
workflow_dispatch     → Build manual com opção de release
```

### Build local
```bash
cd camda-app
cp .env.example .env       # configurar credenciais
flutter pub get
flutter build apk --release
# APK em: build/app/outputs/flutter-apk/app-release.apk
```

---

## 🎨 Guia de Cores

| Token | Escuro | Claro | Uso |
|---|---|---|---|
| `background` | `#0A0F1A` | `#F0F4F8` | Fundo das telas |
| `surface` | `#111827` | `#FFFFFF` | Cards e painéis |
| `green` | `#00D68F` | igual | Status OK, ações primárias |
| `blue` | `#3B82F6` | igual | Códigos, info, destaques |
| `red` | `#FF4757` | igual | Status Falta, erros |
| `amber` | `#FFA502` | igual | Status Sobra, alertas |
| `purple` | `#A55EEA` | igual | Galeria, tertiary |
| `cyan` | `#00C4FF` | igual | Validade ≤90 dias |

---

*Última atualização: março de 2026*
