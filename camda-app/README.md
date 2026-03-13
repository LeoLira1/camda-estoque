# CAMDA App 🌿

**Versão Flutter do Dashboard de Gestão de Estoque CAMDA**

Aplicativo nativo mobile/desktop para gerenciamento do estoque da cooperativa CAMDA, espelhando o dashboard Streamlit existente com visual dark glassmorphism e integração completa com o banco de dados Turso (libSQL).

---

## 📱 Funcionalidades

| Tela | Funcionalidade |
|------|---------------|
| **Login** | Autenticação com senha, widget de clima de Quirinópolis |
| **Dashboard** | KPIs de estoque, alertas de validade, atividade recente |
| **Estoque** | Listagem completa com filtros por status/categoria, busca |
| **Avarias** | Registro e resolução de avarias por produto |
| **Validade** | Alertas de lotes vencidos/críticos/em alerta com gráficos |
| **Reposição** | Lista de itens para repor na loja com marcação de concluído |
| **Vendas** | Histórico de vendas por grupo com gráfico de barras e top produtos |
| **Mapa Visual** | Grid interativo do armazém (10 racks × 2 faces × 13 colunas × 4 níveis), busca de produto por localização, ocupação por rack |

---

## 🎨 Design

- **Tema**: Dark glassmorphism fiel ao dashboard Streamlit
- **Background**: `#0A0F1A`
- **Acento principal**: `#00D68F` (verde)
- **Fonte principal**: Outfit (títulos) + JetBrains Mono (números)
- **Navegação**: BottomNavigationBar (mobile) / NavigationRail (tablet/desktop ≥ 600px)
- **Animações**: flutter_animate para fade-in e transições suaves

---

## 🗄️ Banco de Dados

O app usa a **API HTTP do Turso (libSQL)** para acesso em tempo real ao banco de dados compartilhado com o dashboard Streamlit.

### Tabelas espelhadas

| Tabela | Descrição |
|--------|-----------|
| `estoque_mestre` | Inventário principal |
| `avarias` | Registro de avarias |
| `validade_lotes` | Lotes com data de vencimento |
| `reposicao_loja` | Itens para repor na loja |
| `vendas_historico` | Histórico de vendas |
| `mapa_posicoes` | Posições no armazém |
| `mapa_produtos` | Catálogo de produtos do mapa |
| `racks` | Configuração dos racks |

---

## ⚙️ Configuração

### 1. Variáveis de ambiente

Copie `.env.example` para `.env` e preencha:

```bash
cp .env.example .env
```

```env
TURSO_DATABASE_URL=libsql://seu-banco.turso.io
TURSO_AUTH_TOKEN=seu-token-aqui
CAMDA_PASSWORD=forca
```

### 2. Fontes

Baixe e adicione em `assets/fonts/`:
- [Outfit](https://fonts.google.com/specimen/Outfit): Regular (400), Medium (500), Bold (700), Black (900)
- [JetBrains Mono](https://www.jetbrains.com/lp/mono/): Regular (400), Bold (700)

### 3. Instalar dependências

```bash
flutter pub get
```

### 4. Rodar

```bash
# Desenvolvimento
flutter run

# Android APK
flutter build apk --release

# Web (Codespaces)
flutter run -d web-server --web-port 3000 --web-hostname 0.0.0.0
```

---

## 📂 Estrutura do Projeto

```
lib/
├── main.dart                    # Entry point
├── core/
│   ├── theme/
│   │   ├── app_colors.dart      # Paleta de cores CAMDA
│   │   └── app_theme.dart       # ThemeData dark glassmorphism
│   ├── constants/
│   │   └── app_constants.dart   # Constantes globais
│   └── utils/
│       ├── date_utils.dart      # Formatação de datas (BRT)
│       └── number_utils.dart    # Formatação numérica (pt_BR)
├── data/
│   ├── database/
│   │   └── turso_client.dart    # Cliente HTTP Turso (libSQL)
│   ├── models/
│   │   ├── produto.dart
│   │   ├── avaria.dart
│   │   ├── validade_lote.dart
│   │   ├── reposicao.dart
│   │   ├── venda.dart
│   │   └── mapa_posicao.dart
│   └── repositories/
│       ├── estoque_repository.dart
│       ├── avarias_repository.dart
│       ├── validade_repository.dart
│       ├── reposicao_repository.dart
│       ├── vendas_repository.dart
│       └── mapa_repository.dart
├── features/
│   ├── auth/login_screen.dart
│   ├── dashboard/dashboard_screen.dart
│   ├── estoque/estoque_screen.dart
│   ├── avarias/avarias_screen.dart
│   ├── validade/validade_screen.dart
│   ├── reposicao/reposicao_screen.dart
│   ├── vendas/vendas_screen.dart
│   └── mapa_visual/mapa_screen.dart
└── shared/
    ├── widgets/
    │   ├── glass_card.dart      # GlassCard + SolidCard
    │   ├── stat_card.dart       # StatCard + StatusBadge
    │   └── loading_widget.dart  # Loading / Error / Empty states
    └── layouts/
        └── main_layout.dart     # Navegação adaptativa
```

---

## 🚧 O que ainda precisa ser implementado

### Alta prioridade
- [ ] **Mapa 3D** — Visualização 3D dos racks (placeholder atual é 2D grid)
- [ ] **Upload de planilha** — Importar Excel para atualizar estoque
- [ ] **Lançamentos manuais** — Interface para entrada/saída manual de estoque
- [ ] **Contagem física** — Workflow de contagem item a item
- [ ] **Agenda** — Calendário de tarefas do armazém
- [ ] **Pendências de entrega** — Registro com foto de pendências

### Média prioridade
- [ ] **Princípios Ativos** — Visão por princípio ativo com agrupamento
- [ ] **Histórico de uploads** — Log de importações realizadas
- [ ] **Sync otimístico** — Cache local com sync offline

### Melhorias futuras
- [ ] **Push notifications** — Alertas de vencimento e avarias
- [ ] **Modo offline** — SQLite local com sync posterior
- [ ] **Biometria** — Autenticação por digital/face
- [ ] **Dark/Light toggle** — Opção de tema claro
- [ ] **Export PDF** — Relatórios em PDF

---

## ⚠️ Pontos de atenção na migração

1. **Turso HTTP vs libsql Python**: O dashboard usa `libsql.connect()` com sync nativo; o app usa a API HTTP REST (`/v2/pipeline`). Ambos acessam o mesmo banco — sem conflito.

2. **Autenticação**: A senha é armazenada no `.env` (variável `CAMDA_PASSWORD`). Em produção, considere usar hash seguro ou backend de auth.

3. **Upload de Excel**: O dashboard importa arquivos `.xlsx` via `openpyxl`. No Flutter, isso requer um backend intermediário ou integração com Google Sheets/Drive API.

4. **Mapa 3D** (`mapa_3d_component.py`): Implementado com Three.js/WebGL no Streamlit. No Flutter, pode usar `flutter_gl` ou `model_viewer_plus`, ou manter o grid 2D atual.

5. **Foto de pendências**: A tabela `pendencias_entrega` armazena `foto_base64`. O Flutter suporta câmera via `image_picker` — precisa implementar.

6. **Fuzzy match de princípios ativos**: O Python usa `difflib.get_close_matches` com corte de 0.72. No Dart, precisa implementar lógica equivalente.

---

## 🔧 Dependências principais

```yaml
http: ^1.2.0              # API Turso
flutter_riverpod: ^2.5.1  # Estado
fl_chart: ^0.68.0         # Gráficos
flutter_animate: ^4.5.0   # Animações
glassmorphism: ^3.0.0     # Efeito glass
intl: ^0.19.0             # Formatação pt_BR
flutter_dotenv: ^5.1.0    # Variáveis de ambiente
```

---

*Desenvolvido para a cooperativa CAMDA — Quirinópolis, GO*
