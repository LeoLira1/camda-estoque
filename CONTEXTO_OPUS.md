# CAMDA Estoque — Contexto para Claude Opus

> Documento gerado em 2026-03-15 para contextualizar o Claude Opus sobre todas as modificações
> feitas no projeto Flutter **CAMDA Estoque** na sessão atual.

---

## 1. Visão Geral do Projeto

**CAMDA Estoque** é um app Flutter para controle de estoque de cooperativa agrícola.
Usa banco de dados **Turso (libSQL)** remoto via HTTP. O build do APK é gerado
automaticamente pelo **GitHub Actions** a cada push nas branches `main` ou `claude/**`.

- **Repositório:** `LeoLira1/camda-estoque`
- **Pasta do app:** `camda-app/`
- **Flutter:** 3.24.0 / Dart — Material 3
- **Branch de trabalho:** `claude/update-app-tabs-dark-mode-IKvhK`

---

## 2. Modificações Feitas (Resumo Executivo)

| # | Arquivo | O que foi feito |
|---|---------|-----------------|
| 1 | `main_layout.dart` | Removeu 3 abas; adicionou toggle dark/light mode |
| 2 | `app_theme.dart` | Tema claro + escuro completo; `ValueNotifier<ThemeMode>` global |
| 3 | `main.dart` | Tornou `CamdaApp` reativo ao `themeNotifier` |
| 4 | `estoque_screen.dart` | Código do produto em azul; campo `nota` (cooperado) em azul |
| 5 | `validade_screen.dart` | 6 abas de validade: Vencidos/≤7d/≤30d/≤60d/≤90d/OK |
| 6 | `reposicao/model + repo` | JOIN com `estoque_mestre` para mostrar qtd em estoque |
| 7 | `reposicao_screen.dart` | Cards com código, qtd vendida e qtd em estoque coloridos |
| 8 | `pendencias_screen.dart` | Adapta cores ao tema (surface/scaffoldBackground) |
| 9 | `build-apk.yml` | Build em `claude/**`; Node24; Release automático no main |
| 10 | `CHANGES.md` | Roadmap, arquitetura e guia de cores do projeto |

---

## 3. Detalhes Técnicos por Arquivo

### 3.1 `camda-app/lib/core/theme/app_theme.dart`

**O que foi feito:** Adicionado suporte a tema claro e escuro com `ValueNotifier` global.

**Estrutura atual:**
```dart
// Notifier global — importado por main.dart e main_layout.dart
final themeNotifier = ValueNotifier<ThemeMode>(ThemeMode.dark);

class AppTheme {
  static ThemeData get darkTheme => _build(Brightness.dark);
  static ThemeData get lightTheme => _build(Brightness.light);

  static ThemeData _build(Brightness brightness) {
    final isDark = brightness == Brightness.dark;

    // Paleta dark: bg=#0A0F1A, surface=#111827, text=#E0E6ED
    // Paleta light: bg=#F0F4F8, surface=#FFFFFF, text=#0A1628
    final bgColor      = isDark ? Color(0xFF0A0F1A) : Color(0xFFF0F4F8);
    final surfaceColor = isDark ? Color(0xFF111827) : Color(0xFFFFFFFF);
    ...

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      // IMPORTANTE: usa .copyWith() — não construtor raw ColorScheme()
      colorScheme: (isDark ? const ColorScheme.dark() : const ColorScheme.light()).copyWith(
        primary: AppColors.green,
        surface: surfaceColor,
        onSurface: onSurface,
        onSurfaceVariant: onSurfaceVar,
        outline: borderColor,
        outlineVariant: borderColor.withOpacity(0.5),
        ...
      ),
      scaffoldBackgroundColor: bgColor,
      ...
    );
  }
}
```

**Por que `.copyWith()` e não `ColorScheme()`:**
O construtor `ColorScheme(brightness:...)` em Flutter 3.24 tem campos obrigatórios
adicionais (`surfaceContainerHighest`, etc.) que não existiam em versões anteriores.
O padrão `.dark().copyWith(...)` é mais robusto e compatível.

---

### 3.2 `camda-app/lib/main.dart`

**O que foi feito:** `CamdaApp` agora é `StatelessWidget` que usa `ValueListenableBuilder`
para reagir automaticamente ao `themeNotifier`.

```dart
class CamdaApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<ThemeMode>(
      valueListenable: themeNotifier,
      builder: (context, mode, _) {
        // Atualiza status bar conforme tema
        SystemChrome.setSystemUIOverlayStyle(...);

        return MaterialApp(
          theme: AppTheme.lightTheme,
          darkTheme: AppTheme.darkTheme,
          themeMode: mode,  // <-- controlado pelo notifier
          home: const LoginScreen(),
          ...
        );
      },
    );
  }
}
```

---

### 3.3 `camda-app/lib/shared/layouts/main_layout.dart`

**O que foi feito:**
- Removidas as abas: `MapaScreen`, `VendasScreen`, `PrincipiosAtivosScreen`
- Abas restantes (8): Dashboard, Estoque, Avarias, Validade, Reposição, Lançamentos, Contagem, Pendências
- BottomNav mobile mostra as 4 primeiras (`[0,1,2,3]`) + botão "Mais"
- No sheet "Mais": toggle dark/light com `Switch` + ícone
- No `NavigationRail` (tablet): botão de tema no rodapé
- Todas as cores usam `Theme.of(context)` para suportar ambos os temas

**Toggle de tema (mobile — sheet "Mais"):**
```dart
Row(children: [
  Icon(isDark ? Icons.dark_mode_outlined : Icons.light_mode_outlined,
      color: AppColors.blue, size: 18),
  Switch(
    value: isDark,
    onChanged: (_) {
      themeNotifier.value = isDark ? ThemeMode.light : ThemeMode.dark;
      Navigator.pop(context);
    },
    activeColor: AppColors.blue,
  ),
]),
```

**Toggle de tema (tablet — NavigationRail rodapé):**
```dart
InkWell(
  onTap: () {
    themeNotifier.value = isDark ? ThemeMode.light : ThemeMode.dark;
  },
  child: Container(
    width: 40, height: 40,
    decoration: BoxDecoration(
      color: AppColors.blue.withOpacity(0.12),
      borderRadius: BorderRadius.circular(10),
    ),
    child: Icon(
      isDark ? Icons.light_mode_outlined : Icons.dark_mode_outlined,
      color: AppColors.blue, size: 20,
    ),
  ),
),
```

---

### 3.4 `camda-app/lib/features/estoque/estoque_screen.dart`

**O que foi feito:** Adicionado código do produto e nome do cooperado na listagem.

**Card do produto (subtítulo):**
```dart
subtitle: Column(
  crossAxisAlignment: CrossAxisAlignment.start,
  children: [
    Row(children: [
      Text('Cód: ', style: TextStyle(fontFamily:'JetBrainsMono', fontSize:10, color:AppColors.textMuted)),
      Text(produto.codigo, style: TextStyle(
        fontFamily:'JetBrainsMono', fontSize:10,
        fontWeight:FontWeight.w700, color:AppColors.blue)), // ← código em azul
      if (produto.categoria.isNotEmpty) ...[
        Text(' · ', style: TextStyle(color: AppColors.textDisabled)),
        Flexible(child: Text(produto.categoria, ...)),
      ],
    ]),
    if (produto.nota.isNotEmpty)       // ← cooperado/nota em azul
      Text(produto.nota, style: TextStyle(fontSize:11, fontWeight:FontWeight.w500, color:AppColors.blue)),
    if (produto.observacoes.isNotEmpty)
      Text(produto.observacoes, style: TextStyle(fontSize:10, color:AppColors.textDisabled, fontStyle:FontStyle.italic)),
  ],
),
```

- **Cor do título:** `Theme.of(context).colorScheme.onSurface` (adapta ao tema)
- **Container:** `Theme.of(context).colorScheme.surface` e `.outline`

---

### 3.5 `camda-app/lib/features/validade/validade_screen.dart`

**O que foi feito:** Reescrita completa — de 3 abas para 6 abas com filtros de prazo.

**Estrutura das abas:**
```dart
static const _tabDias = [-1, 7, 30, 60, 90, 0];
// -1 = vencidos | 7/30/60/90 = vencendo em até X dias | 0 = OK (>90d)

_tabController = TabController(length: 6, vsync: this);
```

**TabBar (scrollável, cores por urgência):**
```dart
TabBar(
  isScrollable: true,
  tabAlignment: TabAlignment.start,
  tabs: [
    _buildTabLabel('Vencidos',  AppColors.red),
    _buildTabLabel('≤ 7 dias',  AppColors.statusAvaria),  // laranja
    _buildTabLabel('≤ 30 dias', AppColors.amber),
    _buildTabLabel('≤ 60 dias', Color(0xFFFFCC44)),        // amarelo
    _buildTabLabel('≤ 90 dias', AppColors.cyan),
    _buildTabLabel('OK',        AppColors.green),
  ],
)
```

**Lógica de filtragem por aba:**
```dart
List<ValidadeLote> _itemsParaTab(int dias) {
  if (dias == -1) return _filteredAll.where((l) => l.isVencido).toList();
  if (dias == 0)  return _filteredAll.where((l) => !l.isVencido && l.diasParaVencer > 90).toList();
  return _filteredAll
      .where((l) => !l.isVencido && l.diasParaVencer <= dias)
      .toList()
    ..sort((a, b) => a.diasParaVencer.compareTo(b.diasParaVencer));
}
```

---

### 3.6 `camda-app/lib/data/models/reposicao.dart`

**O que foi feito:** Adicionado campo `qtdEstoque` (quantidade em estoque atual).

```dart
class Reposicao {
  final int id;
  final String codigo;
  final String produto;
  final String categoria;
  final int qtdVendida;
  final String criadoEm;
  final bool pendente;
  final int qtdEstoque;    // ← NOVO

  factory Reposicao.fromMap(Map<String, dynamic> map) => Reposicao(
    ...
    qtdEstoque: _toInt(map['qtd_estoque']),  // ← NOVO
  );
}
```

---

### 3.7 `camda-app/lib/data/repositories/reposicao_repository.dart`

**O que foi feito:** Query `getAll()` faz JOIN com `estoque_mestre` para trazer `qtd_sistema`.

```dart
Future<List<Reposicao>> getAll({bool apenasPendentes = false}) async {
  var sql = '''
    SELECT r.id, r.codigo, r.produto, r.categoria, r.qtd_vendida,
           r.criado_em, r.reposto, r.reposto_em,
           COALESCE(e.qtd_sistema, 0) as qtd_estoque   -- ← NOVO
    FROM reposicao_loja r
    LEFT JOIN estoque_mestre e ON TRIM(r.codigo) = TRIM(e.codigo)  -- ← NOVO
  ''';
  ...
}
```

---

### 3.8 `camda-app/lib/features/reposicao/reposicao_screen.dart`

**O que foi feito:** Adicionados chips coloridos com código, qtd vendida e qtd em estoque.

**Widget `_InfoChip` (novo):**
```dart
class _InfoChip extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: RichText(text: TextSpan(children: [
        TextSpan(text: '$label: ', style: TextStyle(fontSize:10, color:AppColors.textMuted)),
        TextSpan(text: value,      style: TextStyle(fontSize:10, fontWeight:FontWeight.w700, color:color)),
      ])),
    );
  }
}
```

**Uso nos cards:**
```dart
Row(children: [
  _InfoChip(label: 'Vendido', value: '${item.qtdVendida} un.', color: AppColors.amber),
  SizedBox(width: 8),
  _InfoChip(
    label: 'Estoque',
    value: '${item.qtdEstoque} un.',
    color: item.qtdEstoque > 0 ? AppColors.green : AppColors.red,  // ← verde se tem, vermelho se zerado
  ),
]),
```

---

### 3.9 `camda-app/lib/features/pendencias/pendencias_screen.dart`

**O que foi feito:** Adaptado para suportar ambos os temas.

- `Scaffold.backgroundColor` → `Theme.of(context).scaffoldBackgroundColor`
- `_PendenciaCard` container → `Theme.of(context).colorScheme.surface`

---

### 3.10 `.github/workflows/build-apk.yml`

**O que foi feito:**

1. **Build em branches `claude/**`:** APK gerado automaticamente a cada push nessas branches.
2. **Node.js 24:** Variável `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"` no nível do workflow.
3. **Flutter 3.24.0:** Atualizado de 3.22.0.
4. **APK nomeado com versão+data:** `camda-estoque-v1.1.0+2-20260315.apk`
5. **`camda-estoque-latest.apk`:** Sempre sobrescrito no repo para fácil download.
6. **GitHub Release automático:** Criado apenas no push em `main` ou quando `release=true` no `workflow_dispatch`.

**Triggers:**
```yaml
on:
  push:
    branches:
      - main
      - 'claude/**'
  workflow_dispatch:
    inputs:
      release:
        description: 'Publicar como release oficial?'
        default: 'false'
```

**Release:**
```yaml
- name: 🚀 Criar GitHub Release
  if: github.ref == 'refs/heads/main' || github.event.inputs.release == 'true'
  uses: softprops/action-gh-release@v2
  with:
    tag_name: v${{ steps.apk_info.outputs.version }}-${{ steps.apk_info.outputs.date }}
    prerelease: ${{ github.ref != 'refs/heads/main' }}
```

---

## 4. Paleta de Cores (AppColors)

| Constante | Hex | Uso |
|-----------|-----|-----|
| `AppColors.green` | `#2DD4A0` | Primária, OK, selecionado |
| `AppColors.blue` | `#3B9EFF` | Código de produto, cooperado, info |
| `AppColors.amber` | `#FFAA44` | Alerta, sobra, qtd vendida |
| `AppColors.red` | `#FF5C5C` | Erro, vencido, falta, sem estoque |
| `AppColors.cyan` | `#00BCD4` | Validade ≤ 90 dias |
| `AppColors.purple` | `#A78BFA` | Terciária |
| `AppColors.statusAvaria` | laranja | Avarias, ≤ 7 dias validade |

**Tema escuro (padrão):**
- Background: `#0A0F1A`
- Surface (cards): `#111827`
- Surface variante: `#1A2332`
- Texto primário: `#E0E6ED`
- Texto secundário: `#7BAFD4`
- Muted: `#64748B`
- Borda: `#1E293B`

**Tema claro:**
- Background: `#F0F4F8`
- Surface (cards): `#FFFFFF`
- Texto primário: `#0A1628`
- Texto secundário: `#3A6291`
- Muted: `#8A9BB0`
- Borda: `#CBD5E1`

---

## 5. Arquitetura do Banco de Dados (Turso)

Tabelas principais usadas:

| Tabela | Descrição |
|--------|-----------|
| `estoque_mestre` | Produtos com `codigo`, `produto`, `nota` (cooperado), `qtd_sistema`, `status` |
| `reposicao_loja` | Itens a repor: `codigo`, `produto`, `qtd_vendida`, `reposto` |
| `validade_lotes` | Lotes com data de vencimento |
| `avarias` | Registros de avarias |
| `lancamentos` | Movimentações |
| `contagem` | Inventário de contagem |
| `pendencias` | Pendências com fotos |

---

## 6. Padrão de Temas (Como Implementado)

### Regra para widgets que suportam dark/light:

```dart
// ✅ CORRETO — usa o tema do contexto
color: Theme.of(context).scaffoldBackgroundColor,     // fundo da tela
color: Theme.of(context).colorScheme.surface,         // cards/containers
color: Theme.of(context).colorScheme.onSurface,       // texto título
color: Theme.of(context).colorScheme.onSurfaceVariant, // texto secundário
color: Theme.of(context).colorScheme.outline,          // bordas

// ❌ EVITAR — hardcoded, não muda com o tema
color: AppColors.surface,
color: AppColors.textPrimary,
color: const Color(0xFF111827),
```

### Regra para ícones e badges coloridos:
Esses podem continuar com cores fixas (`AppColors.green`, `.blue`, `.red`, etc.)
pois são elementos de UI intencionalmente coloridos em ambos os temas.

---

## 7. Como Fazer Novas Modificações

### Para adicionar uma nova tela:
1. Criar em `camda-app/lib/features/<nome>/<nome>_screen.dart`
2. Importar em `main_layout.dart`
3. Adicionar em `_allScreens` e `_allItems`
4. Decidir se entra no `_bottomIndices` (aparece no BottomNav mobile) ou no "Mais"

### Para fazer uma tela suportar dark/light mode:
- Substituir `AppColors.background` → `Theme.of(context).scaffoldBackgroundColor`
- Substituir `AppColors.surface` → `Theme.of(context).colorScheme.surface`
- Substituir `AppColors.textPrimary` → `Theme.of(context).colorScheme.onSurface`
- Manter cores de status/alerta fixas (green, red, amber, blue)

### Para fazer o build do APK:
1. Commit + push na branch `claude/**` → CI faz o build automaticamente
2. Download do artifact no GitHub Actions (disponível 30 dias)
3. Ou aguardar commit automático do `camda-estoque-latest.apk` no repositório

---

## 8. Problemas Conhecidos e Soluções

### Build do APK falhando

**Sintoma:** `flutter build apk --release` falha com erro de `ColorScheme`.

**Causa:** O construtor `ColorScheme(brightness: ..., ...)` requer campos adicionais
no Flutter 3.24 (`surfaceContainerHighest`, etc.).

**Solução aplicada:** Usar `ColorScheme.dark().copyWith(...)` em vez do construtor raw.

```dart
// ❌ Antes — causava erro de compilação no Flutter 3.24
colorScheme: ColorScheme(
  brightness: brightness,
  primary: AppColors.green,
  surface: surfaceColor,
  ...
),

// ✅ Depois — compatível com Flutter 3.24
colorScheme: (isDark ? const ColorScheme.dark() : const ColorScheme.light()).copyWith(
  primary: AppColors.green,
  surface: surfaceColor,
  ...
),
```

### Aviso "Node.js 20 deprecated" no GitHub Actions

**Sintoma:** Warning nas ações `actions/checkout@v4`, `actions/setup-java@v4`, `actions/cache@v4`.

**Causa:** GitHub Actions está migrando de Node 20 para Node 24.

**Solução aplicada:** `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"` no nível do workflow.

**Nota:** Este aviso é informativo e NÃO impede o build de completar com sucesso.

### Conflitos em Pull Requests

**Sintoma:** PR mostrando conflitos no GitHub mesmo após rebase.

**Causa:** Gitea computa merge base diferente em histórico com octopus merges.

**Solução aplicada:** Criar commit único diretamente sobre `main` usando:
```bash
git diff origin/main...origin/<branch> | git apply --index
git commit -m "squash: todas as mudanças"
git push --force origin <branch>
```

---

## 9. Branch e PR Atual

- **Branch de trabalho:** `claude/update-app-tabs-dark-mode-IKvhK`
- **PR:** #175 (merged com sucesso) / #176 (conflito resolvido por squash)
- **Todos os commits foram enviados** para o remote

---

## 10. Estado Atual

Todas as modificações foram commitadas e enviadas para a branch `claude/update-app-tabs-dark-mode-IKvhK`.
O GitHub Actions deve estar rodando o build do APK. Se houver falha, verificar:

1. Log completo do GitHub Actions (passo "Build APK release")
2. Erros de compilação Dart (análise estática no passo anterior)
3. Secrets configurados: `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, `CAMDA_PASSWORD`
